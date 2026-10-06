import { queryOptions } from "@tanstack/react-query";
import { type CategoryOut, listCategories } from "../api/generated";

export const categoriesQuery = queryOptions({
  queryKey: ["categories"],
  queryFn: async () => (await listCategories({ throwOnError: true })).data,
});

/** <option>s grouped by parent: each parent is selectable, followed by its subcategories. */
export function CategoryOptions({ categories }: { categories: CategoryOut[] }) {
  const parents = categories.filter((c) => c.parent_id === null);
  return (
    <>
      {parents.map((parent) => (
        <optgroup key={parent.id} label={parent.name}>
          <option value={parent.id}>{parent.name}</option>
          {categories
            .filter((c) => c.parent_id === parent.id)
            .map((child) => (
              <option key={child.id} value={child.id}>
                {child.name}
              </option>
            ))}
        </optgroup>
      ))}
    </>
  );
}
