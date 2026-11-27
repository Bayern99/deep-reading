package genuikit

// CatalogJSON returns the embedded authoritative catalog.json bytes so
// downstream packages can derive narrowed component subsets without duplicating it.
func CatalogJSON() []byte {
	return catalog
}
