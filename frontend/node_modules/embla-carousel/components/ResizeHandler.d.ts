import { AxisType } from './Axis';
import { EventHandlerType } from './EventHandler';
import { NodeHandlerType } from './NodeHandler';
import { WindowType } from './utils';
export type ResizeHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
};
export declare function ResizeHandler(active: boolean, container: HTMLElement, eventHandler: EventHandlerType, slides: HTMLElement[], axis: AxisType, nodeHandler: NodeHandlerType): ResizeHandlerType;
