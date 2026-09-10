import { AxisType } from './Axis';
import { EventHandlerType } from './EventHandler';
import { EventStoreType } from './EventStore';
import { ScrollBodyType } from './ScrollBody';
import { ScrollToType } from './ScrollTo';
import { ScrollSnapListType } from './ScrollSnapList';
import { WindowType } from './utils';
export type SlideFocusType = {
    init: (ownerWindow: WindowType) => void;
};
export declare function SlideFocus(axis: AxisType, active: boolean, root: HTMLElement, slides: HTMLElement[], scrollSnapList: ScrollSnapListType, scrollTo: ScrollToType, scrollBody: ScrollBodyType, eventStore: EventStoreType, eventHandler: EventHandlerType): SlideFocusType;
