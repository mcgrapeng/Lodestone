import { NumberStoreInputType } from './utils.js';
export type LimitType = {
    min: number;
    max: number;
    length: number;
    clamp: (input: NumberStoreInputType) => number;
    pastAnyBound: (input: NumberStoreInputType) => boolean;
    pastMaxBound: (input: NumberStoreInputType) => boolean;
    pastMinBound: (input: NumberStoreInputType) => boolean;
    removeOffset: (input: NumberStoreInputType) => number;
};
export declare function Limit(min?: number, max?: number): LimitType;
