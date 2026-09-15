import { AnimationsType } from './Animations.js';
import { CounterType } from './Counter.js';
import { DragTrackerType } from './DragTracker.js';
import { EventHandlerType } from './EventHandler.js';
import { AxisType } from './Axis.js';
import { ScrollBodyType } from './ScrollBody.js';
import { ScrollTargetType } from './ScrollTarget.js';
import { ScrollToType } from './ScrollTo.js';
import { NumberStoreType } from './NumberStore.js';
import { PercentOfViewType } from './PercentOfView.js';
import { WindowType } from './utils.js';
export type DragHandlerType = {
    init: (ownerWindow: WindowType) => void;
    destroy: () => void;
    pointerDown: () => boolean;
};
export declare function DragHandler(active: boolean, axis: AxisType, rootNode: HTMLElement, target: NumberStoreType, dragTracker: DragTrackerType, location: NumberStoreType, animation: AnimationsType, scrollTo: ScrollToType, scrollBody: ScrollBodyType, scrollTarget: ScrollTargetType, indexCurrent: CounterType, eventHandler: EventHandlerType, percentOfView: PercentOfViewType, dragFree: boolean, dragThreshold: number, skipSnaps: boolean, baseFriction: number): DragHandlerType;
