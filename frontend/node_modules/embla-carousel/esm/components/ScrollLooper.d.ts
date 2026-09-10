import { LimitType } from './Limit.js';
import { NumberStoreType } from './NumberStore.js';
export type ScrollLooperType = {
    loop: (direction: number) => void;
};
export declare function ScrollLooper(contentSize: number, limit: LimitType, location: NumberStoreType, loopEntities: NumberStoreType[]): ScrollLooperType;
