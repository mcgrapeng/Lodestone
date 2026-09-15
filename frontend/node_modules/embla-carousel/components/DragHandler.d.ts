import { AnimationsType } from './Animations';
import { CounterType } from './Counter';
import { DragTrackerType } from './DragTracker';
import { EventHandlerType } from './EventHandler';
import { AxisType } from './Axis';
import { ScrollBodyType } from './ScrollBody';
import { ScrollTargetType } from './ScrollTarget';
import { ScrollToType } from './ScrollTo';
import { NumberStoreType } from './NumberStore';
import { PercentOfViewType } from './PercentOfView';
import { WindowType } from './utils';
export type DragHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
    pointerDown: () => boolean;
};
export declare function DragHandler(active: boolean, axis: AxisType, rootNode: HTMLElement, target: NumberStoreType, dragTracker: DragTrackerType, location: NumberStoreType, animation: AnimationsType, scrollTo: ScrollToType, scrollBody: ScrollBodyType, scrollTarget: ScrollTargetType, indexCurrent: CounterType, eventHandler: EventHandlerType, percentOfView: PercentOfViewType, dragFree: boolean, dragThreshold: number, skipSnaps: boolean, baseFriction: number): DragHandlerType;
