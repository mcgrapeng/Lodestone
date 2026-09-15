import { NodeRectType } from './NodeHandler.js';
import { NumberStoreInputType } from './utils.js';
export type AxisOptionType = 'x' | 'y';
export type AxisDirectionOptionType = 'ltr' | 'rtl';
type AxisEdgeType = 'top' | 'right' | 'bottom' | 'left';
export type AxisType = {
    scroll: AxisOptionType;
    cross: AxisOptionType;
    startEdge: AxisEdgeType;
    endEdge: AxisEdgeType;
    nativeScroll: 'scrollLeft' | 'scrollTop';
    getSize: (nodeRect: NodeRectType) => number;
    direction: (input: NumberStoreInputType) => number;
};
export declare function Axis(axis: AxisOptionType, contentDirection: AxisDirectionOptionType): AxisType;
export {};
