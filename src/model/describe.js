/**
 * Summaries for synthetic (demo) graphs. Real graphs carry summaries in the spec (`doc`); the demo maps get
 * plausible text from each service's name and each endpoint's kind, labelled as simulated in the UI.
 */

const ROLE = {
  api: d => `Serves the ${d} API that other services call.`,
  core: d => `Holds the core ${d} logic that the rest of the domain builds on.`,
  worker: d => `Runs background jobs for ${d}, mostly in reaction to events.`,
  gateway: d => `Front door for ${d}: routes and authorises incoming requests.`,
  ui: d => `User interface for ${d}.`,
  web: d => `Web front end for ${d}.`,
  mobile: d => `Backend for the ${d} mobile apps.`,
  admin: d => `Internal admin tools for ${d}.`,
  cms: d => `Content management for ${d}.`,
  sync: d => `Keeps ${d} data in sync with other systems.`,
  resolver: d => `Resolves ${d} references for other services.`,
  pipeline: d => `Processes ${d} data in batches.`,
  ingestor: d => `Takes in ${d} data from outside sources.`,
  indexer: d => `Builds search indexes over ${d} data.`,
  store: d => `Owns ${d} data and how it is stored.`,
  monitor: d => `Watches ${d} health and raises alerts.`,
  engine: d => `Computes ${d} results for the rest of the platform.`,
  bridge: d => `Connects ${d} to external partners.`,
  scheduler: d => `Schedules recurring ${d} work.`,
  router: d => `Routes ${d} traffic between services.`,
  service: d => `Main service for ${d}.`,
  edge: d => `Caches and delivers ${d} content close to users.`,
  shared: d => `Shared ${d} helpers used across the repository.`,
  infra: d => `Infrastructure glue for ${d}.`,
};
const VERB = { GET: 'Returns', POST: 'Creates', PUT: 'Replaces', PATCH: 'Updates', DELETE: 'Deletes' };
const words = s =>
  s
    .replace(/[_/.{}-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

/** One or two plain sentences describing node i of a synthetic graph. */
export function syntheticDoc(g, i) {
  if (i < g.S) {
    const dom = g.domName[g.svcDom[i]];
    const parts = g.svcName[i].split('_');
    const suffix = [...parts].reverse().find(p => ROLE[p]);
    return (ROLE[suffix] || ROLE.service)(dom);
  }
  const name = g.name(i),
    svc = g.svcName[g.own(i)];
  const http = name.match(/^(GET|POST|PUT|PATCH|DELETE) (\S+)/);
  if (http) return `${VERB[http[1]]} ${words(http[2])} for clients of ${svc}.`;
  const evt = name.match(/^([\w-]+)\.([\w-]+)$/);
  if (evt) return `Event that ${svc} publishes when ${words(evt[1])} is ${words(evt[2])}.`;
  return `Internal module of ${svc} (${name}).`;
}
