export type CounterType = {
    get: () => number;
    set: (input: number) => CounterType;
    add: (input: number) => CounterType;
    clone: () => CounterType;
};
export declare function Counter(max: number, start: number, loop: boolean): CounterType;
