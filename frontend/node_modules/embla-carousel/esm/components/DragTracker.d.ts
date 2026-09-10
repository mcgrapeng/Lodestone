import { AxisOptionType, AxisType } from './Axis.js';
import { WindowType } from './utils.js';
export type PointerEventType = TouchEvent | MouseEvent;
export type DragTrackerType = {
    init: (ownerWindow: WindowType) => void;
    pointerDown: (evt: PointerEventType) => number;
    pointerMove: (evt: PointerEventType) => number;
    pointerUp: (evt: PointerEventType) => number;
    readPoint: (evt: PointerEventType, evtAxis?: AxisOptionType) => number;
};
export declare function DragTracker(axis: AxisType): DragTrackerType;
