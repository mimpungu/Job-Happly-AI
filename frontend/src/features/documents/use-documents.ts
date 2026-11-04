"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { generateLetter, generateResume, listLetters, listResumes } from "@/services/documents";

const resumesKey = ["documents", "resumes"] as const;
const lettersKey = ["documents", "letters"] as const;

export const useResumes = () => useQuery({ queryKey: resumesKey, queryFn: listResumes });
export const useLetters = () => useQuery({ queryKey: lettersKey, queryFn: listLetters });

/** Les choix de documents de la fiche candidature en dépendent : on les relit aussi. */
function useInvalidate(key: readonly string[]) {
  const client = useQueryClient();
  return async () => {
    await client.invalidateQueries({ queryKey: key });
    await client.invalidateQueries({ queryKey: ["applications"] });
  };
}

export function useGenerateResume() {
  const invalider = useInvalidate(resumesKey);
  return useMutation({ mutationFn: generateResume, onSuccess: invalider });
}

export function useGenerateLetter() {
  const invalider = useInvalidate(lettersKey);
  return useMutation({ mutationFn: generateLetter, onSuccess: invalider });
}
