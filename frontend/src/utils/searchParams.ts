export const cloneSearchParams = (searchParams: URLSearchParams) => {
  return new URLSearchParams(searchParams)
}

export const setOptionalSearchParam = (
  searchParams: URLSearchParams,
  key: string,
  value: string | null | undefined,
) => {
  if (value) {
    searchParams.set(key, value)
  } else {
    searchParams.delete(key)
  }
}

export const replaceMultiValueSearchParam = (
  searchParams: URLSearchParams,
  key: string,
  values: string[],
) => {
  searchParams.delete(key)
  values.forEach((value) => searchParams.append(key, value))
}
