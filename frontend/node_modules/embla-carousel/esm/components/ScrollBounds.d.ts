import { LimitType } from './Limit.js';
import { ScrollBodyType } from './ScrollBody.js';
import { NumberStoreType } from './NumberStore.js';
import { PercentOfViewType } from './PercentOfView.js';
export type ScrollBoundsType = {
    shouldConstrain: () => boolean;
    constrain: (pointerDown: boolean) => void;
    toggleActive: (active: boolean) => void;
};
export declare function ScrollBounds(limit: LimitType, location: NumberStoreType, target: NumberStoreType, scrollBody: ScrollBodyType, percentOfView: PercentOfViewType): ScrollBoundsType;
