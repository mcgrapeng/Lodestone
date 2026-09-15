import { AxisType } from './Axis.js';
import { EventHandlerType } from './EventHandler.js';
import { NodeHandlerType } from './NodeHandler.js';
import { WindowType } from './utils.js';
export type ResizeHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
};
export declare function ResizeHandler(active: boolean, container: HTMLElement, eventHandler: EventHandlerType, slides: HTMLElement[], axis: AxisType, nodeHandler: NodeHandlerType): ResizeHandlerType;
