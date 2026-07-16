export type RadarTarget = {
  id: number;
  angle: number;
  distance: number;
  speed: number;
};

export type SensorNode = {
  id: string;
  room: string;
  co2: number;
  pirOut: boolean;
  pirIn: boolean;
  mmwaveTargets: number;
  status: "online" | "offline";
  battery: number | null;
};

export type RoomState = {
  room: string;
  occupancy: number;
  capacity: number;
  level: "safe" | "near-limit" | "over";
};

export type Alert = {
  id: string;
  kind: "capacity" | "co2" | "offline";
  title: string;
  detail: string;
  time: string;
};

export type OccupancyPoint = { t: string; count: number };

export type OccupancyRange = "1H" | "6H" | "1D" | "1W" | "1M";

const occupancy1D: OccupancyPoint[] = [
  { t: "12A", count: 4 }, { t: "2A", count: 3 }, { t: "4A", count: 2 },
  { t: "6A", count: 5 }, { t: "8A", count: 14 }, { t: "10A", count: 21 },
  { t: "12P", count: 26 }, { t: "2P", count: 30 }, { t: "4P", count: 25 },
  { t: "6P", count: 18 }, { t: "8P", count: 9 }, { t: "10P", count: 4 },
];

const occupancy1H: OccupancyPoint[] = [
  { t: ":00", count: 22 }, { t: ":05", count: 23 }, { t: ":10", count: 25 },
  { t: ":15", count: 27 }, { t: ":20", count: 26 }, { t: ":25", count: 28 },
  { t: ":30", count: 29 }, { t: ":35", count: 28 }, { t: ":40", count: 26 },
  { t: ":45", count: 24 }, { t: ":50", count: 25 }, { t: ":55", count: 24 },
];

const occupancy6H: OccupancyPoint[] = [
  { t: "9A", count: 12 }, { t: "9:30", count: 16 }, { t: "10A", count: 21 },
  { t: "10:30", count: 24 }, { t: "11A", count: 27 }, { t: "11:30", count: 29 },
  { t: "12P", count: 26 }, { t: "12:30", count: 22 }, { t: "1P", count: 25 },
  { t: "1:30", count: 28 }, { t: "2P", count: 30 }, { t: "2:30", count: 27 },
];

const occupancy1W: OccupancyPoint[] = [
  { t: "Mon", count: 27 }, { t: "Tue", count: 31 }, { t: "Wed", count: 24 },
  { t: "Thu", count: 33 }, { t: "Fri", count: 20 }, { t: "Sat", count: 4 },
  { t: "Sun", count: 2 },
];

const occupancy1M: OccupancyPoint[] = [
  { t: "W1", count: 22 }, { t: "W2", count: 26 }, { t: "W3", count: 25 }, { t: "W4", count: 29 },
];

export const occupancySeriesByRange: Record<OccupancyRange, OccupancyPoint[]> = {
  "1H": occupancy1H,
  "6H": occupancy6H,
  "1D": occupancy1D,
  "1W": occupancy1W,
  "1M": occupancy1M,
};

// Live radar targets — shape matches the RD-03D UART frame the team is
// parsing in Thonny (angle / distance / speed per target, up to 3).
export const radarTargets: RadarTarget[] = [
  { id: 1, angle: -6.2, distance: 469.8, speed: 0 },
  { id: 2, angle: 0, distance: 0, speed: 0 },
  { id: 3, angle: 0, distance: 0, speed: 0 },
];

export const sensorNodes: SensorNode[] = [
  { id: "NODE-01", room: "K17-101", co2: 720, pirOut: true, pirIn: false, mmwaveTargets: 1, status: "online", battery: 82 },
  { id: "NODE-02", room: "K17-101", co2: 735, pirOut: false, pirIn: false, mmwaveTargets: 1, status: "online", battery: 76 },
  { id: "NODE-03", room: "K17-102", co2: 980, pirOut: true, pirIn: true, mmwaveTargets: 2, status: "online", battery: 68 },
  { id: "NODE-04", room: "K17-103", co2: 1250, pirOut: true, pirIn: false, mmwaveTargets: 0, status: "offline", battery: null },
  { id: "NODE-05", room: "K17-104", co2: 560, pirOut: false, pirIn: false, mmwaveTargets: 0, status: "online", battery: 91 },
];

export const rooms: RoomState[] = [
  { room: "K17-101", occupancy: 24, capacity: 40, level: "safe" },
  { room: "K17-102", occupancy: 38, capacity: 40, level: "near-limit" },
  { room: "K17-103", occupancy: 44, capacity: 40, level: "over" },
  { room: "K17-104", occupancy: 12, capacity: 30, level: "safe" },
];

export const alerts: Alert[] = [
  { id: "a1", kind: "capacity", title: "Over capacity", detail: "K17-103 is over capacity (44/40)", time: "10:20 AM" },
  { id: "a2", kind: "co2", title: "High CO\u2082 level", detail: "K17-102 CO\u2082 reading is high (980 ppm)", time: "10:18 AM" },
  { id: "a3", kind: "offline", title: "Node offline", detail: "NODE-04 in K17-103 stopped reporting", time: "10:15 AM" },
];