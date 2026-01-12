import { describe, it, expect } from "vitest";
import {
  generateCodeVerifier,
  generateCodeChallenge,
  generateState,
} from "../pkce";

describe("PKCE utilities", () => {
  describe("generateCodeVerifier", () => {
    it("generates a string of correct length", () => {
      const verifier = generateCodeVerifier();
      // Base64url encoding of 32 bytes = 43 characters
      expect(verifier.length).toBe(43);
    });

    it("generates unique values", () => {
      const verifier1 = generateCodeVerifier();
      const verifier2 = generateCodeVerifier();
      expect(verifier1).not.toBe(verifier2);
    });

    it("generates URL-safe characters only", () => {
      const verifier = generateCodeVerifier();
      // Base64url should only contain alphanumeric, dash, and underscore
      expect(verifier).toMatch(/^[A-Za-z0-9_-]+$/);
    });
  });

  describe("generateCodeChallenge", () => {
    it("generates a SHA-256 hash of the verifier", async () => {
      const verifier = "test-verifier-string";
      const challenge = await generateCodeChallenge(verifier);

      // Challenge should be base64url encoded
      expect(challenge).toMatch(/^[A-Za-z0-9_-]+$/);
      // SHA-256 produces 32 bytes = 43 base64url chars
      expect(challenge.length).toBe(43);
    });

    it("produces consistent output for same input", async () => {
      const verifier = "test-verifier";
      const challenge1 = await generateCodeChallenge(verifier);
      const challenge2 = await generateCodeChallenge(verifier);
      expect(challenge1).toBe(challenge2);
    });

    it("produces different output for different input", async () => {
      const challenge1 = await generateCodeChallenge("verifier1");
      const challenge2 = await generateCodeChallenge("verifier2");
      expect(challenge1).not.toBe(challenge2);
    });
  });

  describe("generateState", () => {
    it("generates a string of correct length", () => {
      const state = generateState();
      // Base64url encoding of 16 bytes = 22 characters
      expect(state.length).toBe(22);
    });

    it("generates unique values", () => {
      const state1 = generateState();
      const state2 = generateState();
      expect(state1).not.toBe(state2);
    });

    it("generates URL-safe characters only", () => {
      const state = generateState();
      expect(state).toMatch(/^[A-Za-z0-9_-]+$/);
    });
  });
});
