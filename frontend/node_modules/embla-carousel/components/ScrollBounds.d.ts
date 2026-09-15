import { LimitType } from './Limit';
import { ScrollBodyType } from './ScrollBody';
import { NumberStoreType } from './NumberStore';
import { PercentOfViewType } from './PercentOfView';
export type ScrollBoundsType = {
    shouldConstrain: () => boolean;
    constrain: (pointerDown: boolean) => void;
    toggleActive: (active: boolean) => void;
};
export declare function ScrollBounds(limit: LimitType, location: NumberStoreType, target: NumberStoreType, scrollBody: ScrollBodyType, percentOfView: PercentOfViewType): ScrollBoundsType;
