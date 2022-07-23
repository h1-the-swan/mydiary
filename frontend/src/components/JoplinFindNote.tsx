import { LoadingOutlined } from "@ant-design/icons";
import { Button, Spin } from "antd";
import React, { useEffect, useState } from "react";
import { useJoplinGetNoteId, useJoplinSync } from "../api";

interface Props {
  dt: string;
  setNoteId: (noteId: string) => any;
  lastSync: Date | undefined;
  setLastSync: (lastSync: Date) => any;
  mutationJoplinSync: any;
}

export default function JoplinFindNote(props: Props) {
  // const [lastSync, setLastSync] = useState<Date>();
  const { lastSync, setLastSync, mutationJoplinSync } = props;
  const noteId = useJoplinGetNoteId(props.dt, {
    query: {
      queryKey: [props.dt, lastSync],
    },
  });
  useEffect(() => {
    if (noteId.data) {
      props.setNoteId(noteId.data.data);
    }
    console.log(noteId);
  }, [noteId, props]);

  function handleButtonClick() {
    mutationJoplinSync.mutate();
  }
  return (
    <>
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
            <p>
              Joplin Note ID: <a href={`joplin://x-callback-url/openNote?id=${noteId.data.data}`}>{noteId.data.data}</a>
              {noteId.isFetching && <Spin indicator={<LoadingOutlined />} />}
            </p>
          )}
        </div>
      )}
    </>
  );
}
