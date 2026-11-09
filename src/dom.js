/**
 * References to the page's fixed elements (see index.html). Looked up once; the page markup is static.
 */
import { $ } from './util/dom.js';

export const app = $('#app');
export const glc = $('#gl');
export const ov = $('#ov');
export const oc = ov.getContext('2d');
export const RT = $('#route');
export const ASK = $('#ask');
export const ATTN = $('#attn');
export const LINKS = $('#links');
export const INSP = $('#insp');
export const Q = $('#q');
export const RES = $('#results');
export const LEGB = $('#legendBody');
export const WHERE = $('#where');
export const SR = $('#sr');
export const TOAST = $('#toast');
// zoom slider: log scale between the dataset's zoom limits, zooming around the centre of the view
export const ZS = $('#zoom');
/* map dock: one tooltip that slides to the hovered or focused button */
export const DOCK = $('#dock');
export const TIP = $('#dockTip');
export const PERF = $('#perf');
export const BLD = $('#building');
