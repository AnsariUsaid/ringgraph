// cytoscape-fcose ships no type declarations. The layout is registered through
// cytoscape.use() and then configured by name, so declaring the module is
// enough -- the options are checked at the call site as LayoutOptions.
declare module "cytoscape-fcose" {
  import type { Ext } from "cytoscape";
  const fcose: Ext;
  export default fcose;
}
