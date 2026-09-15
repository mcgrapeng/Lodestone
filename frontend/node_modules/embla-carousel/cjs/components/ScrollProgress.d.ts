import { LimitType } from './Limit';
import { NumberStoreInputType } from './utils';
export type ScrollProgressType = {
    get: (input: NumberStoreInputType) => number;
};
export declare function ScrollProgress(limit: LimitType): ScrollProgressType;
