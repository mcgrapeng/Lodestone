import { LimitType } from './Limit.js';
import { DirectionType } from './ScrollTo.js';
import { NumberStoreType } from './NumberStore.js';
export type TargetType = {
    distance: number;
    index: number;
};
export type ScrollTargetType = {
    byIndex: (target: number, direction: DirectionType) => TargetType;
    byDistance: (force: number, snapToClosest: boolean) => TargetType;
    shortcut: (target: number, direction: DirectionType) => number;
};
export declare function ScrollTarget(loop: boolean, scrollSnaps: number[], contentSize: number, limit: LimitType, targetVector: NumberStoreType): ScrollTargetType;
