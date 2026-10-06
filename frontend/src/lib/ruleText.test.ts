import { expect, test } from "vitest";
import { suggestRuleText } from "./ruleText";

test.each([
  ["CARTE X0000 13/03 BOULANGERIE DU PARC 100000000000001IOPD", "BOULANGERIE DU PARC"],
  ["CARTE X0000 28/02 PHARMACIE DE L'ÉGLISE 100000000000005IOPD", "PHARMACIE DE L'ÉGLISE"],
  [
    "PRELEVEMENT EUROPEEN 0000000001 DE: ENERGIE EXEMPLE SA ID: FR00ZZZ000001 MOTIF: Echeance electricite mars",
    "ENERGIE EXEMPLE SA",
  ],
  [
    "VIR RECU    0000000001A DE: EMPLOYEUR EXEMPLE SAS MOTIF: SALAIRE DE FEVRIER 2026 REF: A000000001",
    "EMPLOYEUR EXEMPLE SAS",
  ],
  ["000001 VIR PERM POUR: JEAN DUPONT REF: 000000000001 MOTIF: Epargne mensuelle", "JEAN DUPONT"],
  ["COTISATION JAZZ", "COTISATION JAZZ"],
  ["INTERETS CREDITEURS", "INTERETS CREDITEURS"],
  ["Sunday market", "Sunday market"],
])("suggestRuleText(%s)", (label, expected) => {
  expect(suggestRuleText(label)).toBe(expected);
});
