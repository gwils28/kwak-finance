import { expect, test } from "vitest";
import { de } from "./frenchDe";

test("de elides before a vowel, accented or not", () => {
  expect(de("Apport maison")).toBe("d'Apport maison");
  expect(de("Été")).toBe("d'Été");
  expect(de("épargne")).toBe("d'épargne");
  expect(de("Voyage au Japon")).toBe("de Voyage au Japon");
  // An aspirated h does not elide ("de Hawaï"): h is left alone.
  expect(de("Hawaï")).toBe("de Hawaï");
});
