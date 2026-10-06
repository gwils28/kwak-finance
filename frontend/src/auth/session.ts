import { queryOptions } from "@tanstack/react-query";
import { me } from "../api/generated";

/** The signed-in user. Fails while there is no fully verified session (password + TOTP). */
export const meQuery = queryOptions({
  queryKey: ["me"],
  queryFn: async () => {
    const { data, error } = await me();
    if (error !== undefined || data === undefined) throw new Error("not signed in");
    return data;
  },
  retry: false,
  staleTime: Number.POSITIVE_INFINITY,
});
