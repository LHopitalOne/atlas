// The layout uses d3-hierarchy as a global (loaded by a <script> tag in the page). Provide it under Node.
import * as d3 from 'd3-hierarchy';
globalThis.d3 = d3;
