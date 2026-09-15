import { AxisType } from './Axis.js';
import { NumberStoreInputType } from './utils.js';
export type TranslateType = {
    to: (input: NumberStoreInputType) => void;
    toggleActive: (active: boolean) => void;
    clear: () => void;
};
export declare function Translate(axis: AxisType, node: HTMLElement): TranslateType;
