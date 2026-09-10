import { AxisType } from './Axis';
import { NumberStoreInputType } from './utils';
export type TranslateType = {
    to: (input: NumberStoreInputType) => void;
    toggleActive: (active: boolean) => void;
    clear: () => void;
};
export declare function Translate(axis: AxisType, node: HTMLElement): TranslateType;
