import { EventHandlerType } from './EventHandler.js';
import { WindowType } from './utils.js';
export type SlidesHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
};
export declare function SlidesHandler(active: boolean, container: HTMLElement, eventHandler: EventHandlerType): SlidesHandlerType;
