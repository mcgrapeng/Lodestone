import { AxisType } from './Axis.js';
import { NodeHandlerType } from './NodeHandler.js';
import { NodeRectType } from './NodeHandler.js';
export type SlideSizesType = {
    slideSizes: number[];
    slideSizesWithGaps: number[];
    startGap: number;
    endGap: number;
};
export declare function SlideSizes(axis: AxisType, containerRect: NodeRectType, slideRects: NodeRectType[], slides: HTMLElement[], readEdgeGap: boolean, nodeHandler: NodeHandlerType): SlideSizesType;
