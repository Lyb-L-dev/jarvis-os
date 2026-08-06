/**
 * Jarvis Web API client — compatibility layer (Sprint 4).
 *
 * The API client has been split by domain into lib/api/*.ts. This module
 * re-exports the original public surface so existing components keep their
 * `@/lib/api` imports untouched (export signature freeze). Do not add new
 * logic here; add it to the corresponding domain module under lib/api/.
 *
 * Domains: system / knowledge / chat / memory / growth / english /
 * intelligence / investment / notifications / tools / observatory / career /
 * cost / context / personality / proactive / computer.
 */

export { API_BASE_URL } from "./api/client";
export * from "./api/system";
export * from "./api/knowledge";
export * from "./api/chat";
export * from "./api/memory";
export * from "./api/growth";
export * from "./api/english";
export * from "./api/intelligence";
export * from "./api/investment";
export * from "./api/notifications";
export * from "./api/tools";
export * from "./api/observatory";
export * from "./api/career";
export * from "./api/cost";
export * from "./api/context";
export * from "./api/personality";
export * from "./api/proactive";
export * from "./api/computer";
