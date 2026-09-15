import { AxisType } from './Axis.js';
import { EventHandlerType } from './EventHandler.js';
import { EventStoreType } from './EventStore.js';
import { ScrollBodyType } from './ScrollBody.js';
import { ScrollToType } from './ScrollTo.js';
import { ScrollSnapListType } from './ScrollSnapList.js';
import { WindowType } from './utils.js';
export type SlideFocusType = {
    init: (ownerWindow: WindowType) => void;
};
export declare function SlideFocus(axis: AxisType, active: boolean, root: HTMLElement, slides: HTMLElement[], scrollSnapList: ScrollSnapListType, scrollTo: ScrollToType, scrollBody: ScrollBodyType, eventStore: EventStoreType, eventHandler: EventHandlerType): SlideFocusType;
