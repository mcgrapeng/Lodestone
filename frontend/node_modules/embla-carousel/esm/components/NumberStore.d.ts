import { NumberStoreInputType } from './utils.js';
export type NumberStoreType = {
    get: () => number;
    set: (input: NumberStoreInputType) => void;
    add: (input: NumberStoreInputType) => void;
    subtract: (input: NumberStoreInputType) => void;
    plus: (input: NumberStoreInputType) => number;
    minus: (input: NumberStoreInputType) => number;
};
export declare function NumberStore(initialValue: number): NumberStoreType;
