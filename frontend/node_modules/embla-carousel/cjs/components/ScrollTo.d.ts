import { AnimationsType } from './Animations';
import { CounterType } from './Counter';
import { EventHandlerType } from './EventHandler';
import { ScrollBodyType } from './ScrollBody';
import { ScrollTargetType } from './ScrollTarget';
import { NumberStoreType } from './NumberStore';
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
