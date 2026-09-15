import { LimitType } from './Limit';
import { DirectionType } from './ScrollTo';
import { NumberStoreType } from './NumberStore';
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
