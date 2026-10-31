import './setup.js';
import { buildSpec } from '../src/model/spec.js';

/**
 * A tiny graph for tests:
 *   repo A: domain a1 { s0 (leaves 3,4), s1 (leaf 5) }, domain a2 { s2 }
 *   repo B: domain b1 { s3? } -> ids: services 0..3, leaves 4..6
 * Calls: s0 -> s1 (via leaves), s1 -> s2, s3 -> s2 (so s0 reaches s2 forwards, s3 only backwards)
 */
export function tinySpec() {
  return {
    meta: {
      status: ['Resolved', 'Ambiguous', 'Unresolved', 'Inferred'],
      kind: ['Definition', 'Function', 'Event', 'Value'],
    },
    repos: [
      {
        name: 'A',
        domains: [
          {
            name: 'a1',
            services: [
              {
                name: 's0',
                leaves: [
                  { name: 'l0', kind: 3 },
                  { name: 'l1', kind: 1 },
                ],
              },
              { name: 's1', leaves: [{ name: 'l2', kind: 1 }] },
            ],
          },
          { name: 'a2', services: [{ name: 's2' }] },
        ],
      },
      { name: 'B', domains: [{ name: 'b1', services: [{ name: 's3' }] }] },
    ],
    // node ids: services s0=0 s1=1 s2=2 s3=3, leaves l0=4 l1=5 l2=6
    edges: [
      [4, 6, 0],
      [1, 2, 0],
      [3, 2, 2],
    ],
  };
}
export const tinyGraph = () => buildSpec(tinySpec());
