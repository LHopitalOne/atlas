"""Plugin URL mounts: Django apps that add their URLconf through an AppConfig's `plugin_app` (edx-django-utils)."""

from ...scope import Scope
from ...syntax import PythonSyntax
from ...values import Marker


class PluginMounts:
    """`plugin_app = {PluginURLs.CONFIG: {ProjectType.LMS: {PluginURLs.REGEX: 'api/x/', PluginURLs.RELATIVE_PATH:
    'urls'}}}` in an AppConfig mounts `<app>.urls` at 'api/x/'. The app is the AppConfig's `name`, else the package
    the apps.py file is in. Each project type's config is one mount."""

    NEEDLE = b'plugin_app'
    ATTRIBUTE = 'plugin_app'
    REGEX_KEY, PATH_KEY = 'REGEX', 'RELATIVE_PATH'  # the ends of the PluginURLs constants used as keys
    DEFAULT_PATH = 'urls'

    def __init__(self, workspace, values):
        self._workspace = workspace
        self._values = values

    def mounts(self):
        """(URLconf module file, regex) for each plugin URL config in the repository's production code."""
        out = []
        for source in self._workspace.sources:
            if source.test or not source.mentions(self.NEEDLE):
                continue
            for cls in PythonSyntax.walk(source.root, {'class_definition'}):
                out += self._class_mounts(source, cls)
        return out

    def _class_mounts(self, source, cls):
        assigned = self._class_assignments(cls)
        config = assigned.get(self.ATTRIBUTE)
        if config is None or config.type != 'dictionary':
            return []
        app = self._app_name(source, assigned.get('name'))
        out = []
        for d in PythonSyntax.walk(config, {'dictionary'}):
            pairs = self._pairs(d)
            regex = pairs.get(self.REGEX_KEY)
            if regex is None:
                continue
            text = self._literal(source, regex)
            relative = self._literal(source, pairs[self.PATH_KEY]) if self.PATH_KEY in pairs else self.DEFAULT_PATH
            module_file = self._workspace.names.dotted_module(f'{app}.{relative}') if text is not None else None
            if module_file is not None:
                out.append((module_file, text))
        return out

    @staticmethod
    def _class_assignments(cls):
        """{name: value node} of the plain assignments in a class body."""
        body = cls.child_by_field_name('body')
        out = {}
        for st in body.named_children if body is not None else ():
            e = st.named_children[0] if st.type == 'expression_statement' and st.named_children else None
            if e is not None and e.type == 'assignment' and e.child_by_field_name('left').type == 'identifier':
                out[PythonSyntax.text(e.child_by_field_name('left'))] = e.child_by_field_name('right')
        return out

    @staticmethod
    def _pairs(dictionary):
        """{last part of the key's name: value node} of a dict literal's pairs."""
        out = {}
        for p in dictionary.named_children:
            if p.type == 'pair':
                key = PythonSyntax.text(p.child_by_field_name('key')).split('.')[-1]
                out[key] = p.child_by_field_name('value')
        return out

    def _app_name(self, source, name_node):
        """The AppConfig's dotted `name`, else the package of its file."""
        if name_node is not None:
            text = self._literal(source, name_node)
            if text:
                return text
        return source.path.rsplit('/', 1)[0].replace('/', '.')

    def _literal(self, source, node):
        v = self._values.resolve(node, Scope.module(source))[0]
        return v.text if v.is_literal and not Marker.names(v.text) else None
