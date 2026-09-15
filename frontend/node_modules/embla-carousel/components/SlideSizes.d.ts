import { AxisType } from './Axis';
import { NodeHandlerType } from './NodeHandler';
import { NodeRectType } from './NodeHandler';
export type SlideSizesType = {
    slideSizes: number[];
    slideSizesWithGaps: number[];
    startGap: number;
    endGap: number;
};
export declare function SlideSizes(axis: AxisType, containerRect: NodeRectType, slideRects: NodeRectType[], slides: HTMLElement[], readEdgeGap: boolean, nodeHandler: NodeHandlerType): SlideSizesType;
