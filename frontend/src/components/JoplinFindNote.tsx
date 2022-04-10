import { Button } from "antd";
import React, { useEffect, useState } from "react";
import { useJoplinGetNoteId, useJoplinSync } from "../api";

interface Props {
  dt: string;
  setNoteId: (noteId: string) => any;
}

export default function JoplinFindNote(props: Props) {
  const [lastSync, setLastSync] = useState<Date>();
  const noteId = useJoplinGetNoteId(props.dt, {
    query: {
      queryKey: [lastSync],
    },
  });
  useEffect(() => {
    if (noteId.data) {
      props.setNoteId(noteId.data.data);
    }
  }, [noteId, props]);
  const mutationJoplinSync = useJoplinSync({
    mutation: {
      onSuccess: () => setLastSync(new Date()),
    },
  });

  function handleButtonClick() {
    mutationJoplinSync.mutate();
  }
  return (
    <>
      {lastSync ? <p>{`Last Joplin sync: ${lastSync}`}</p> : null}
      {noteId.isLoading && <span>Loading...</span>}
      {noteId.isError && <span>Error: {noteId.error.message}</span>}
      {noteId.isSuccess && (
        <div>
          {noteId.data.data === "does_not_exist" ? (
            <>
              <p>Note not found</p>
              <Button
                onClick={handleButtonClick}
                loading={mutationJoplinSync.isLoading}
              >
                Sync and Try Again
              </Button>
            </>
          ) : (
            <p>Joplin Note ID: {noteId.data.data}</p>
          )}
        </div>
      )}
    </>
  );
}
