#!/usr/bin/env python3
"""Index Atlas's own source into a graph spec (docs/GRAPH_SPEC.md) that the Self map displays.

  tree-sitter (JavaScript, CSS, HTML grammars): structure. Modules, top-level definitions, inner functions,
              object members, event handlers, CSS rules, markup elements, GLSL declarations.
  SCIP (scip-typescript): precise resolution of every reference across modules, including into TypeScript's
              lib.dom / lib.es declarations.

Edge status:
  0 Resolved    SCIP resolved the reference (or an exact name match for CSS / markup / GLSL varyings)
  1 Ambiguous   resolved, but the name is defined more than once in the same file (shadowing)
  2 Unresolved  nothing resolves it: untyped globals, classes without a rule, undefined custom properties
  3 Inferred    tree-sitter heuristics over string literals: selectors, class names, shader uniforms

Usage: python3 tools/index-self/index_self.py <repo-root> <scip-json> <out.json>
"""
import json, os, re, sys, glob
from collections import defaultdict
from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs, tree_sitter_css as tscss, tree_sitter_html as tshtml

ROOT, SCIP_JSON, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SRC = os.path.join(ROOT, 'src')
cap = lambda s: s[:1].upper() + s[1:]

# ---------------------------------------------------------------- graph model
class Graph:
    def __init__(self): self.repos = {}; self.edges = set()
    def svc(self, repo, domain, name, loc='', **extra):
        doms = self.repos.setdefault(repo, {})
        for d in doms.values():
            if name in d: return d[name]
        s = {'id': (repo, name), 'name': name, 'loc': loc, 'leaves': {}, **{k: v for k, v in extra.items() if v}}
        doms.setdefault(domain, {})[name] = s; return s
    def leaf(self, svc, name, kind, loc='', **extra):
        base, k = name, 2
        if name in svc['leaves'] and svc['leaves'][name]['kind'] != kind:
            while name in svc['leaves']: name = f'{base} ({k})'; k += 1
        if name not in svc['leaves']: svc['leaves'][name] = {'id': (svc['id'], name), 'name': name, 'kind': kind, 'loc': loc, **{k: v for k, v in extra.items() if v}}
        return svc['leaves'][name]
    def edge(self, a, b, st):
        if a is not None and b is not None and a['id'] != b['id']: self.edges.add((a['id'], b['id'], st))
G = Graph()

def layer(mod):
    top = mod.split('/')[0]
    return {'model': 'Model', 'graph': 'Model', 'render': 'Render', 'app': 'App', 'ask': 'App', 'ui': 'UI', 'dom': 'UI'}.get(top, 'Core')

# ---------------------------------------------------------------- JavaScript modules (tree-sitter)
JSP = Parser(Language(tsjs.language()))
FUNCS = ('arrow_function', 'function_expression', 'function', 'generator_function')
files = sorted(p for p in glob.glob(os.path.join(SRC, '**', '*.js'), recursive=True))
mods = {}   # rel path -> dict(src, lines, tree, nodes(list of ranges), defpos, top)
for path in files:
    rel = os.path.relpath(path, ROOT).replace(os.sep, '/')
    B = open(path, encoding='utf-8').read().encode('utf-8')
    mods[rel] = {'B': B, 'lines': B.split(b'\n'), 'tree': JSP.parse(B), 'nodes': [], 'defpos': {}, 'top': {}, 'names': defaultdict(int)}

def u16(m, row, bcol): return len(m['lines'][row][:bcol].decode('utf-8', 'ignore').encode('utf-16-le')) // 2
def to_byte(m, row, ucol):
    starts = m.setdefault('ls', None)
    if starts is None:
        starts = [0]
        for ln in m['lines'][:-1]: starts.append(starts[-1] + len(ln) + 1)
        m['ls'] = starts
    line = m['lines'][row].decode('utf-8', 'ignore')
    return starts[row] + len(line[:ucol].encode('utf-8'))
def txt(m, n): return m['B'][n.start_byte:n.end_byte].decode('utf-8', 'ignore')
def loc(rel, n): return f"{rel[4:] if rel.startswith('src/') else rel}:{n.start_point[0] + 1}"

def doc_of(m, node):
    """The JSDoc or // comment right above a declaration, as plain sentences (first paragraph, no @tags)."""
    p = node.prev_sibling
    while p is not None and p.type != 'comment' and p.type in (',', ';'): p = p.prev_sibling
    if p is None or p.type != 'comment' or p.end_point[0] < node.start_point[0] - 1: return ''
    t = txt(m, p)
    if t.startswith('//'): body = t[2:]
    else: body = re.sub(r'^\s*\*\s?', '', t[2:-2].lstrip('*'), flags=re.M)
    para = []
    for line in body.strip().split('\n'):
        line = line.strip()
        if line.startswith('@') or (not line and para): break
        if line: para.append(line)
    out = ' '.join(para)
    return out if len(out) <= 320 else out[:317].rsplit(' ', 1)[0] + '…'

def sig_of(m, node, name):
    """One-line signature: name and parameters for functions, the start of the value otherwise."""
    one = lambda t: ' '.join(t.split())
    target = node
    if node.type == 'variable_declarator':
        v = node.child_by_field_name('value')
        if v is not None and v.type in FUNCS:
            ps = v.child_by_field_name('parameters') or v.child_by_field_name('parameter')
            return one(f"{name} = {txt(m, ps) if ps is not None else '()'} =>")[:160]
        first = txt(m, v).split('\n')[0] if v is not None else ''
        return one(f"{name} = {first}")[:120] + ('…' if v is not None and ('\n' in txt(m, v) or len(first) > 100) else '')
    if node.type in ('function_declaration', 'method_definition', 'pair'):
        f = node if node.type != 'pair' else node.child_by_field_name('value')
        ps = f.child_by_field_name('parameters') if f is not None else None
        if ps is not None: return one(f"{'function ' if node.type == 'function_declaration' else ''}{name}{txt(m, ps)}")[:160]
    return one(txt(m, target).split('\n')[0])[:120]

def end_of(node): return node.end_point[0] + 1

def reg(m, rel, node_range, gnode, name_node=None):
    m['nodes'].append((node_range.start_byte, node_range.end_byte, gnode))
    if name_node is not None:
        m['defpos'][(name_node.start_point[0], u16(m, name_node.start_point[0], name_node.start_point[1]))] = gnode
        m['names'][gnode['name']] += 1

def is_listener(m, call):
    f = call.child_by_field_name('function')
    return f is not None and f.type == 'member_expression' and f.child_by_field_name('property') is not None and txt(m, f.child_by_field_name('property')) == 'addEventListener'
def listener(m, call):
    args = call.child_by_field_name('arguments')
    if not args or args.named_child_count < 2 or args.named_children[0].type != 'string': return None, None
    return txt(m, args.named_children[0]).strip('\'"'), args.named_children[1]

def collect_leaves(m, rel, root, svc, top_obj=None):
    stack = [root]
    while stack:
        n = stack.pop(); t = n.type
        if t == 'function_declaration' and n is not root:
            nm = n.child_by_field_name('name'); lf = G.leaf(svc, txt(m, nm), 1, loc(rel, n), doc=doc_of(m, n), sig=sig_of(m, n, txt(m, nm)), end=end_of(n)); reg(m, rel, n, lf, nm)
        elif t == 'variable_declarator' and n is not root:
            nm, v = n.child_by_field_name('name'), n.child_by_field_name('value')
            if nm is not None and nm.type == 'identifier' and v is not None and v.type in FUNCS:
                lf = G.leaf(svc, txt(m, nm), 1, loc(rel, n), doc=doc_of(m, n.parent), sig=sig_of(m, n, txt(m, nm)), end=end_of(n)); reg(m, rel, v, lf, nm)
        elif t in ('pair', 'method_definition') and n.parent is not None and n.parent is top_obj:
            key = n.child_by_field_name('key') if t == 'pair' else n.child_by_field_name('name')
            v = n.child_by_field_name('value') if t == 'pair' else n
            if key is not None:
                fn = t == 'method_definition' or (v is not None and v.type in FUNCS)
                kname = txt(m, key).strip('\'"')
                lf = G.leaf(svc, kname, 1 if fn else 3, loc(rel, n), doc=doc_of(m, n), sig=sig_of(m, n, kname), end=end_of(n)); reg(m, rel, v if v is not None else n, lf, key)
        elif t == 'shorthand_property_identifier' and n.parent is not None and n.parent is top_obj:
            lf = G.leaf(svc, txt(m, n), 3, loc(rel, n)); reg(m, rel, n, lf, n)
        elif t == 'call_expression' and is_listener(m, n):
            ev, h = listener(m, n)
            if ev: lf = G.leaf(svc, f'on {ev}', 2, loc(rel, n), sig=' '.join(txt(m, n).split('\n')[0].split())[:120], end=end_of(n)); reg(m, rel, h, lf)
        stack.extend(reversed(n.children))

for rel, m in mods.items():
    modname = rel[4:-3]                      # e.g. render/labels
    repo, dom = layer(modname), modname
    for st in m['tree'].root_node.named_children:
        decl = st
        if st.type == 'export_statement':
            decl = st.child_by_field_name('declaration') or next((c for c in st.named_children if c.type in ('function_declaration', 'lexical_declaration', 'variable_declaration', 'class_declaration')), None)
            if decl is None: continue
        if decl.type in ('function_declaration', 'class_declaration'):
            nm = decl.child_by_field_name('name')
            s = G.svc(repo, dom, txt(m, nm), loc(rel, decl), doc=doc_of(m, st), sig=('export ' if st.type == 'export_statement' else '') + sig_of(m, decl, txt(m, nm)), end=end_of(decl))
            reg(m, rel, decl, s, nm); m['top'][txt(m, nm)] = s; collect_leaves(m, rel, decl, s)
        elif decl.type in ('lexical_declaration', 'variable_declaration'):
            for d in decl.named_children:
                if d.type != 'variable_declarator': continue
                nm, v = d.child_by_field_name('name'), d.child_by_field_name('value')
                kw = txt(m, decl).split()[0]
                s = G.svc(repo, dom, txt(m, nm), loc(rel, d), doc=doc_of(m, st) if d is decl.named_children[0] else '',
                          sig=('export ' if st.type == 'export_statement' else '') + kw + ' ' + sig_of(m, d, txt(m, nm)), end=end_of(d))
                reg(m, rel, d, s, nm); m['top'][txt(m, nm)] = s
                if v is not None: collect_leaves(m, rel, v, s, top_obj=v if v.type == 'object' else None)
        elif st.type == 'expression_statement':
            s = G.svc(repo, dom, f'{modname} (top level)', loc(rel, st), end=end_of(st)); reg(m, rel, st, s)
    m['nodes'].sort(key=lambda r: r[1] - r[0])

def enclosing(m, b):
    for s, e, nd in m['nodes']:
        if s <= b < e: return nd
    return None
def owner(nd): return nd['id'][0] if isinstance(nd['id'][0], tuple) else nd['id']

# ---------------------------------------------------------------- SCIP: resolve every reference
scip = json.load(open(SCIP_JSON))
docs = {d['relative_path']: d for d in scip['documents']}
sym2node, occ_starts = {}, defaultdict(set)
for rel, m in mods.items():
    d = docs.get(rel)
    if not d: continue
    for o in d.get('occurrences', []):
        r = o['range']; occ_starts[rel].add((r[0], r[1]))
        if o.get('symbol_roles', 0) & 1 and (r[0], r[1]) in m['defpos']:
            key = (rel, o['symbol']) if o['symbol'].startswith('local ') else o['symbol']
            sym2node.setdefault(key, m['defpos'][(r[0], r[1])])

EXT = 'Web platform'
def ext_target(sym):
    mm = re.match(r'scip-typescript npm typescript [\d.]+ lib/`(lib\.[\w.]+\.d\.ts)`/(.+)$', sym)
    if not mm: return None
    lib, desc = mm.groups()
    if ').(' in desc: return None
    desc = desc.rstrip('.')
    owner_, member = desc.split('#', 1) if '#' in desc else ('globals', desc)
    member = member.rstrip('./').replace('()', ''); owner_ = owner_.rstrip('/')
    if not member or '#' in member: return None
    dom = ('WebGL' if owner_.startswith('WebGL') else 'Canvas 2D' if owner_.startswith('Canvas') or owner_ in ('Path2D', 'TextMetrics')
           else 'Browser globals' if owner_ == 'globals' else 'DOM' if lib == 'lib.dom.d.ts' else 'JavaScript built-ins')
    return G.leaf(G.svc(EXT, dom, owner_), member, 1 if '()' in desc or desc.endswith(')') else 3)

for rel, m in mods.items():
    d = docs.get(rel)
    if not d: continue
    for o in d.get('occurrences', []):
        if o.get('symbol_roles', 0) & 1: continue
        r = o['range']; src = enclosing(m, to_byte(m, r[0], r[1]))
        if src is None: continue
        sym = o['symbol']
        tgt = sym2node.get((rel, sym) if sym.startswith('local ') else sym)
        if tgt is not None:
            if owner(src) == owner(tgt): continue
            tmod = next((mm2 for mm2 in mods.values() if any(n is tgt for _, _, n in mm2['nodes'])), None)
            G.edge(src, tgt, 1 if tmod is not None and tmod['names'][tgt['name']] > 1 else 0)
        elif not sym.startswith('local '):
            t2 = ext_target(sym)
            if t2: G.edge(src, t2, 0)

# unresolved: identifiers / globalThis properties that SCIP has no symbol for
UNTYPED = 'Untyped globals'
def walk(n):
    yield n
    for c in n.children: yield from walk(c)
for rel, m in mods.items():
    for n in walk(m['tree'].root_node):
        name, holder = None, None
        if n.type == 'identifier' and (n.start_point[0], u16(m, *n.start_point)) not in occ_starts[rel]:
            p = n.parent
            if p is not None and p.type in ('variable_declarator', 'formal_parameters', 'catch_clause', 'import_specifier'): continue
            if txt(m, n) in ('globalThis', 'window', 'undefined'): continue
            name, holder = txt(m, n), n
        elif n.type == 'property_identifier' and n.parent is not None and n.parent.type == 'member_expression' \
                and txt(m, n.parent.child_by_field_name('object')) in ('globalThis', 'window') \
                and (n.start_point[0], u16(m, *n.start_point)) not in occ_starts[rel]:
            name, holder = txt(m, n), n.parent
        if not name: continue
        src = enclosing(m, n.start_byte)
        if src is None: continue
        s = G.svc(UNTYPED, 'No type information', name); tgt = s
        p = holder.parent
        if p is not None and p.type == 'member_expression' and p.child_by_field_name('object') == holder:
            tgt = G.leaf(s, txt(m, p.child_by_field_name('property')), 1)
        G.edge(src, tgt, 2)

# ---------------------------------------------------------------- page: CSS and markup (tree-sitter)
H = open(os.path.join(SRC, 'index.html'), encoding='utf-8').read()
CSS_S = H.index('<style>') + len('<style>'); CSS = H[CSS_S:H.index('</style>')]; CSS_L0 = H.count('\n', 0, CSS_S)
B_S = H.index('<body>'); BODY = H[B_S:H.index('<script type="application/json"')]; B_L0 = H.count('\n', 0, B_S)
STY, MARKUP = 'Styles', 'Markup'
CB = CSS.encode('utf-8'); css_tree = Parser(Language(tscss.language())).parse(CB)
ctxt = lambda n: CB[n.start_byte:n.end_byte].decode('utf-8', 'ignore')
cloc = lambda n: f"index.html:{CSS_L0 + n.start_point[0] + 1}"
class_svc, token_leaf, rule_vars, section = {}, {}, [], 'Tokens'
def css_banner(t):
    mm = re.match(r'/\*\s*-{4,}\s*(.+?)\s*-{4,}\s*\*/', t, re.S)
    return cap(re.split(r'\s\(|:\s', mm.group(1))[0].strip()) if mm else None
def handle_rule(rs, media=''):
    sel = next((c for c in rs.children if c.type == 'selectors'), None)
    if sel is None: return
    stext = ' '.join(ctxt(sel).split())
    mm = re.search(r'\.([a-zA-Z][\w-]*)', stext) or re.search(r'(#[\w-]+)', stext)
    key = ('.' + mm.group(1)) if mm and not mm.group(1).startswith('#') else (mm.group(1) if mm else stext.split(',')[0].split(':not')[0].strip())
    s = G.svc(STY, section, key, cloc(rs))
    for c in re.findall(r'\.([a-zA-Z][\w-]*)', stext): class_svc.setdefault(c, s)
    lf = G.leaf(s, (stext if len(stext) <= 56 else stext[:55] + '…') + (f' {media}' if media else ''), 3, cloc(rs))
    block = next((c for c in rs.children if c.type == 'block'), None)
    for decl in (block.named_children if block else []):
        if decl.type != 'declaration': continue
        prop = ctxt(decl.named_children[0]) if decl.named_children else ''
        if prop.startswith('--'): token_leaf.setdefault(prop, G.leaf(G.svc(STY, 'Tokens', ':root tokens', cloc(decl)), prop, 3, cloc(decl)))
        for v in re.findall(r'var\((--[\w-]+)', ctxt(decl)): rule_vars.append((lf, v))
for n in css_tree.root_node.named_children:
    if n.type == 'comment':
        b = css_banner(ctxt(n)); section = b or section
    elif n.type == 'rule_set': handle_rule(n)
    elif n.type == 'media_statement':
        q = ' '.join(ctxt(n).split('{', 1)[0].replace('@media', '').split()); q = '@' + (q if len(q) < 40 else q[:39] + '…')
        blk = next((c for c in n.children if c.type == 'block'), None)
        for c in (blk.named_children if blk else []):
            if c.type == 'rule_set': handle_rule(c, q)
all_js = ''.join(m['B'].decode('utf-8', 'ignore') for m in mods.values())
inline_vars = set(re.findall(r'(--[\w-]+):', all_js))
for lf, v in rule_vars:
    if v in token_leaf: G.edge(lf, token_leaf[v], 0)
    elif v in inline_vars: G.edge(lf, G.leaf(G.svc(STY, 'Tokens', 'inline tokens'), v + ' (set from script)', 3), 3)
    else: G.edge(lf, G.leaf(G.svc(STY, 'Missing', 'undefined tokens'), v, 3), 2)
def class_target(c):
    if c in class_svc: return class_svc[c], 0
    return G.svc(STY, 'Missing', f'.{c} (no rule)'), 2

BB = BODY.encode('utf-8'); html_tree = Parser(Language(tshtml.language())).parse(BB)
htxt = lambda n: BB[n.start_byte:n.end_byte].decode('utf-8', 'ignore')
hloc = lambda n: f"index.html:{B_L0 + n.start_point[0] + 1}"
REGION = {'tl':'Header','toolbar':'Toolbar','br':'Map controls','legend':'Key','where':'Location','insp':'Inspector','route':'Directions','attn':'Needs attention',
          'toast':'Toast','building':'Loading','nogl':'Fallback','gl':'Map canvas','ov':'Map canvas','mapHelp':'Map canvas','sr':'Live region'}
def attrs(el):
    st = next((c for c in el.children if c.type in ('start_tag', 'self_closing_tag')), None); out, tag = {}, ''
    for c in (st.children if st else []):
        if c.type == 'tag_name': tag = htxt(c)
        if c.type == 'attribute':
            k = next((x for x in c.children if x.type == 'attribute_name'), None)
            v = next((x for x in c.children if x.type in ('quoted_attribute_value', 'attribute_value')), None)
            if k is not None: out[htxt(k)] = htxt(v).strip('"\'') if v is not None else ''
    return tag, out
def visit(el, region, own):
    tag, a = attrs(el)
    if tag in ('script', 'svg', 'path', 'circle', 'option', 'span', 'i', 'b', 'p') and 'id' not in a: return
    node = own
    if 'id' in a: node = G.svc(MARKUP, region, '#' + a['id'], hloc(el))
    elif tag in ('button', 'input', 'select', 'summary', 'canvas') and own is not None:
        label = a.get('aria-label') or a.get('data-tip') or ' '.join(re.sub(r'<[^>]+>', ' ', htxt(el)).split())[:28] or tag
        node = G.leaf(own, f'{tag} “{label}”', 1, hloc(el))
    for c in a.get('class', '').split():
        if node is not None: t, st = class_target(c); G.edge(node, t, st)
    for c in el.children:
        if c.type == 'element': visit(c, region, node if node is not None else own)
def find_app(n):
    if n.type == 'element' and attrs(n)[1].get('id') == 'app': return n
    for c in n.children:
        r = find_app(c)
        if r: return r
app = find_app(html_tree.root_node)
G.svc(MARKUP, 'Document', '#app', hloc(app)); G.svc(MARKUP, 'Document', '#selfGraph', 'index.html')
for ch in app.children:
    if ch.type != 'element': continue
    tag, a = attrs(ch); key = a.get('id') or (a.get('class', '').split() or [tag])[0]; region = REGION.get(key, cap(key))
    own = G.svc(MARKUP, region, '#' + a['id'] if 'id' in a else f'{tag}.{key}', hloc(ch))
    for c in a.get('class', '').split(): t, st = class_target(c); G.edge(own, t, st)
    for c in ch.children:
        if c.type == 'element': visit(c, region, own)
runtime_ids = set(re.findall(r'id="([\w-]+)"', all_js))
def markup_target(i):
    for doms in G.repos.get(MARKUP, {}).values():
        if '#' + i in doms: return doms['#' + i], 3
    if i in runtime_ids or i.startswith('opt-') or i.startswith('rtopt-'): return G.svc(MARKUP, 'Created at runtime', '#' + i), 3
    return G.svc(MARKUP, 'Missing', f'#{i} (no element)'), 2

# ---------------------------------------------------------------- shaders (GLSL in render/gl.js)
gl_rel = 'src/render/gl.js'; GLJS = mods[gl_rel]['B'].decode('utf-8')
uni = {}
for mm in re.finditer(r'(P_\w+): \[(`.*?`),\s*(`.*?`)\]', GLJS, re.S):
    pname = mm.group(1); stages = {}
    for stage, src, off in (('vertex', mm.group(2), mm.start(2)), ('fragment', mm.group(3), mm.start(3))):
        s = G.svc('Shaders', pname, f'{pname} {stage}', f"render/gl.js:{GLJS[:off].count(chr(10)) + 1}"); stages[stage] = s
        G.edge(mods[gl_rel]['top'].get(pname), s, 0)
        for um in re.finditer(r'uniform\s+\w+\s+(\w+)', src):
            uni.setdefault((pname, um.group(1)), G.leaf(s, um.group(1), 3, f"render/gl.js:{GLJS[:off + um.start()].count(chr(10)) + 1}"))
        for im in re.finditer(r'(?:layout\(location=\d\)\s*)?\b(flat\s+)?(in|out)\s+\w+\s+(\w+)\s*;', src):
            if stage == 'fragment' and im.group(2) == 'out': continue
            G.leaf(s, f'{im.group(2)} {im.group(3)}', 3, f"render/gl.js:{GLJS[:off + im.start()].count(chr(10)) + 1}")
    for lf in list(stages['fragment']['leaves'].values()):
        if lf['name'].startswith('in '):
            v = stages['vertex']['leaves'].get('out ' + lf['name'][3:])
            if v: G.edge(lf, v, 0)

# ---------------------------------------------------------------- inferred links from string literals
for rel, m in mods.items():
    for n in walk(m['tree'].root_node):
        src = enclosing(m, n.start_byte)
        if src is None: continue
        if n.type == 'call_expression':
            f = n.child_by_field_name('function'); args = n.child_by_field_name('arguments')
            fname = txt(m, f) if f is not None else ''
            first = args.named_children[0] if args is not None and args.named_child_count else None
            if first is not None and first.type == 'string' and (fname == '$' or fname.endswith(('querySelector', 'querySelectorAll', 'closest', 'getElementById'))):
                sel = txt(m, first).strip('\'"')
                if fname.endswith('getElementById'): sel = '#' + sel
                for i in re.findall(r'#([\w-]+)', sel): t, st = markup_target(i); G.edge(src, t, st)
                for c in re.findall(r'\.([a-zA-Z][\w-]*)', sel): t, st = class_target(c); G.edge(src, t, 3 if st == 0 else st)
            if first is not None and re.search(r'classList\.(add|remove|toggle|contains)$', fname):
                for a in args.named_children:
                    if a.type == 'string': t, st = class_target(txt(m, a).strip('\'"')); G.edge(src, t, 3 if st == 0 else st)
        elif n.type in ('template_string', 'string'):
            s = txt(m, n)
            for cl in re.findall(r'class="([^"$]+)"', s):
                for c in cl.split():
                    if re.match(r'^[a-zA-Z][\w-]*$', c): t, st = class_target(c); G.edge(src, t, 3 if st == 0 else st)
            tm = re.fullmatch(r"'(--[\w-]+)'", s)
            if tm:
                t = token_leaf.get(tm.group(1))
                G.edge(src, t if t else G.leaf(G.svc(STY, 'Missing', 'undefined tokens'), tm.group(1), 3), 3 if t else 2)
        elif n.type == 'member_expression':
            mm = re.fullmatch(r'(P_\w+)\.u\.(u_\w+)', txt(m, n))
            if mm and (mm.group(1), mm.group(2)) in uni: G.edge(src, uni[(mm.group(1), mm.group(2))], 3)

# ---------------------------------------------------------------- emit spec
ORDER = [r for r in ['Core', 'Model', 'Render', 'App', 'UI', STY, MARKUP, 'Shaders', EXT, UNTYPED] if r in G.repos]
ids, out_repos, sid, services = {}, [], 0, []
for r in ORDER:
    doms = []
    for dname, svcs in G.repos[r].items():
        if not svcs: continue
        sv = []
        for s in svcs.values():
            ids[s['id']] = sid; sid += 1; services.append(s)
            pick = lambda o, keys: {k: o[k] for k in keys if o.get(k)}
            sv.append({**pick(s, ('name', 'loc', 'end', 'sig', 'doc')),
                       'leaves': [{**pick(l, ('name', 'loc', 'end', 'sig', 'doc')), 'kind': l['kind']} for l in s['leaves'].values()]})
        doms.append({'name': dname, 'services': sv})
    out_repos.append({'name': r, 'domains': doms})
lid = sid
for s in services:
    for l in s['leaves'].values(): ids[l['id']] = lid; lid += 1
edges = sorted({(ids[a], ids[b], st) for a, b, st in G.edges if a in ids and b in ids and ids[a] != ids[b]})
import tree_sitter as _ts
tool = scip['metadata'].get('tool_info', {})
import subprocess
def git(*a):
    try: return subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception: return ''
commit = git('log', '-1', '--format=%h', '--', 'src')
spec = {'meta': {'title': 'Atlas, indexed by itself', 'commit': commit or 'working tree', 'docSource': 'comment', 'sourceBundle': 'selfSource', 'status': ['Resolved', 'Ambiguous name', 'Unresolved', 'Inferred'],
                 'kind': ['Definition', 'Function or control', 'Event handler', 'Value, rule or uniform'],
                 'source': f"tree-sitter {getattr(_ts, '__version__', '')} + {tool.get('name', 'scip-typescript')} {tool.get('version', '')}".strip()},
        'repos': out_repos, 'edges': edges}
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
json.dump(spec, open(OUT, 'w'), separators=(',', ':'), ensure_ascii=False)
# source bundle: stands in for "fetched live from GitHub" in the prototype (paths as used in `loc`)
files = {rel[4:]: m['B'].decode('utf-8') for rel, m in mods.items()}
files['index.html'] = H
json.dump({'commit': commit or 'working tree', 'files': files}, open(os.path.join(os.path.dirname(OUT), 'self-source.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
cnt = defaultdict(int)
for e in edges: cnt[e[2]] += 1
print(f'{len(files)} modules -> {sid} definitions, {lid - sid} members, {len(edges)} links {dict(cnt)}')
for r in out_repos: print(f"  {r['name']:16s} {len(r['domains']):3d} domains {sum(len(d['services']) for d in r['domains']):4d} definitions")
