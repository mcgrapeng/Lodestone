import { LimitType } from './Limit.js';
import { NumberStoreInputType } from './utils.js';
export type ScrollProgressType = {
    get: (input: NumberStoreInputType) => number;
};
export declare function ScrollProgress(limit: LimitType): ScrollProgressType;
