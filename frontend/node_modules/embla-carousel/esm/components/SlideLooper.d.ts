import { NumberStoreType } from './NumberStore.js';
import { TranslateType } from './Translate.js';
type LoopPointType = {
    loopPoint: number;
    index: number;
    translate: TranslateType;
    slideLocation: NumberStoreType;
    target: () => number;
};
export type SlideLooperType = {
    canLoop: () => boolean;
    loop: () => void;
    loopPoints: LoopPointType[];
};
export declare function SlideLooper(viewSize: number, contentSize: number, slideSizes: number[], slideSizesWithGaps: number[], snaps: number[], scrollSnaps: number[], location: NumberStoreType, slideTranslates: TranslateType[]): SlideLooperType;
export {};
