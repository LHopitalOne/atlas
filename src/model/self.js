/** The embedded graph shown as "Self": Atlas's own code by default, or any graph passed to Atlas.loadGraph(). */
let SELF = null;
export const selfSpec = () => SELF || (SELF = JSON.parse(document.getElementById('selfGraph').textContent));
/** Replace the embedded graph (used by Atlas.loadGraph). */
export const setSelfSpec = spec => {
  SELF = spec;
};
