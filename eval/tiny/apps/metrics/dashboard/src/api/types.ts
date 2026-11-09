export interface Point {
  value: number;
  ts: number;
  tags: Record<string, string>;
}

export interface Series {
  name: string;
  points: Point[];
}

export interface Summary {
  name: string;
  count: number;
  min: number;
  max: number;
  mean: number;
  last: number;
}
