import { NumberStoreType } from './NumberStore';
export type ScrollBodyType = {
    direction: () => number;
    duration: () => number;
    velocity: () => number;
    seek: () => ScrollBodyType;
    settled: () => boolean;
    useBaseFriction: () => ScrollBodyType;
    useBaseDuration: () => ScrollBodyType;
    useFriction: (input: number) => ScrollBodyType;
    useDuration: (input: number) => ScrollBodyType;
};
export declare function ScrollBody(location: NumberStoreType, offsetLocation: NumberStoreType, previousLocation: NumberStoreType, target: NumberStoreType, baseDuration: number, baseFriction: number): ScrollBodyType;
