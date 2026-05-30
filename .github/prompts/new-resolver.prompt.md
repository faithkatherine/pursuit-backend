---
description: "Add a GraphQL query or mutation resolver to the Pursuit backend"
---

Add a new GraphQL ${input:resolverType:query or mutation} named ${input:resolverName}.

Before writing:

- Read the relevant app's existing resolvers to match the pattern
- Check graphql/queries.ts in the frontend to see if this is already expected

Resolver requirements:

- Use select_related for all FK traversals — prevents N+1
- If query result is cacheable, add Redis cache-aside with appropriate TTL:
  weather: 30min, recommendations: 60min, home aggregate: 15min
- Cache keys must include userId at minimum
- If resolver touches location data: check allow_location_sharing before returning coords
- Return null (not empty) for location/weather fields when allow_location_sharing=false

If this is a mutation:

- Wrap in a transaction if multiple model writes
- Return updated object so Apollo client can update cache
- If mutation changes allowLocationSharing: null out lat/lng when disabling

After creating the resolver:

- Add the type to the GraphQL schema
- Note: run npm run codegen in the frontend after the schema is updated
