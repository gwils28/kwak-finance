/** French "de" before a name: "d'" before a vowel ("d'Apport maison"), "de" otherwise. An h is
 * left alone, since an aspirated one does not elide ("de Hawaï"). */
export const de = (name: string) =>
  /^[aeiouyàâäéèêëîïôöùûüÿæœ]/i.test(name) ? `d'${name}` : `de ${name}`;
