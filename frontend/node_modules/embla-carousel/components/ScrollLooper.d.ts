import { LimitType } from './Limit';
import { NumberStoreType } from './NumberStore';
export type ScrollLooperType = {
    loop: (direction: number) => void;
};
export declare function ScrollLooper(contentSize: number, limit: LimitType, location: NumberStoreType, loopEntities: NumberStoreType[]): ScrollLooperType;
