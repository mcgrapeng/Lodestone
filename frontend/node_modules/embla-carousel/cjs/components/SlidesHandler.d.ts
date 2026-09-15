import { EventHandlerType } from './EventHandler';
import { WindowType } from './utils';
export type SlidesHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
};
export declare function SlidesHandler(active: boolean, container: HTMLElement, eventHandler: EventHandlerType): SlidesHandlerType;
