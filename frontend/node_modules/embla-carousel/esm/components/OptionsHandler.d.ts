import { NodeHandlerType } from './NodeHandler.js';
import { LooseOptionsType, CreateOptionsType } from './Options.js';
type OptionsType = Partial<CreateOptionsType<LooseOptionsType>>;
export type OptionsHandlerType = {
    init: (ownerWindow: NodeHandlerType['ownerWindow']) => void;
    mergeOptions: <TypeA extends OptionsType, TypeB extends OptionsType>(optionsA: TypeA, optionsB?: TypeB) => TypeA;
    optionsAtMedia: <Type extends OptionsType>(options: Type) => Type;
    optionsMediaQueries: (optionsList: OptionsType[]) => MediaQueryList[];
};
export declare function OptionsHandler(): OptionsHandlerType;
export {};
