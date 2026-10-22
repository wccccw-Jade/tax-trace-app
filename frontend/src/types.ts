export type Actor = {id:string;name:string;role:string;sensitive_data_clearance?:boolean};
export type Locator = {resolved:boolean;layer:string;start:number;end:number;quote:string;actor?:string;at?:string};
export type Trace = {revision:number|null;kind:string;page?:{printed_content:string}|null;ref:string;value:Record<string,unknown>;edges:{source:string;target:string;kind:string}[]};
export type Extraction = {ref:string;revision:number;payload:{page:number;field:string;label:string;value:unknown;locator:Locator}};
