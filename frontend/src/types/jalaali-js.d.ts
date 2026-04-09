declare module "jalaali-js" {
  /** Convert Gregorian date to Jalaali */
  export function toJalaali(gy: number, gm: number, gd: number): { jy: number; jm: number; jd: number };
  export function toJalaali(date: Date): { jy: number; jm: number; jd: number };

  /** Convert Jalaali date to Gregorian */
  export function toGregorian(jy: number, jm: number, jd: number): { gy: number; gm: number; gd: number };

  /** Check if a Jalaali year is leap */
  export function isLeapJalaaliYear(jy: number): boolean;

  /** Check validity of a Jalaali date */
  export function isValidJalaaliDate(jy: number, jm: number, jd: number): boolean;

  /** Number of days in a Jalaali month */
  export function jalaaliMonthLength(jy: number, jm: number): number;
}

