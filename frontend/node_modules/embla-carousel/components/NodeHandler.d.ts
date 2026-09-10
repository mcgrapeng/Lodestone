import { OptionsType } from './Options';
import { WindowType } from './utils';
export type NodeRectType = {
    top: number;
    right: number;
    bottom: number;
    left: number;
    width: number;
    height: number;
};
export type NodeRectsType = {
    containerRect: NodeRectType;
    slideRects: NodeRectType[];
};
export type NodesType = {
    root: HTMLElement;
    container: HTMLElement;
    slides: HTMLElement[];
};
export type NodeHandlerType = {
    ownerDocument: Document | null;
    ownerWindow: WindowType | null;
    getNodes: (options: OptionsType) => NodesType;
    getRect: (node: HTMLElement) => NodeRectType;
    getRects: (container: HTMLElement, slides: HTMLElement[], fromCache?: boolean) => NodeRectsType;
};
export declare function NodeHandler(root?: HTMLElement | null): NodeHandlerType;
