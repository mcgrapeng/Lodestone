import { AnimationsType } from './Animations.js';
import { CounterType } from './Counter.js';
import { EventHandlerType } from './EventHandler.js';
import { ScrollBodyType } from './ScrollBody.js';
import { ScrollTargetType } from './ScrollTarget.js';
import { NumberStoreType } from './NumberStore.js';
export type DirectionType = 0 | 1 | -1;
export type ScrollToDirectionType = 'forward' | 'backward' | DirectionType;
export type SelectEventType = {
    targetSnap: number;
    sourceSnap: number;
};
export type ScrollToType = {
    distance: (input: number, snapToClosest: boolean) => void;
    index: (input: number, direction?: ScrollToDirectionType) => void;
};
export declare function ScrollTo(animation: AnimationsType, indexCurrent: CounterType, indexPrevious: CounterType, scrollBody: ScrollBodyType, scrollTarget: ScrollTargetType, targetVector: NumberStoreType, eventHandler: EventHandlerType): ScrollToType;
