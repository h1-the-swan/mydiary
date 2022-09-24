import React, { useCallback, useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Form, Button, Alert, DatePicker, Space } from "antd";
import { useJoplinSync, useJoplinInitNote, useJoplinUpdateNote } from "../api";
import JoplinFindNote from "../components/JoplinFindNote";
import moment from "moment";

const TestJoplin = () => {
  const [noteId, setNoteId] = useState<string>();
  const [lastSync, setLastSync] = useState<Date>();
  const [searchParams, setSearchParams] = useSearchParams();
  if (!searchParams.get("dt")) {
    setSearchParams({ dt: "yesterday" });
  }
  const dt = searchParams.get("dt") || "yesterday";
  let dtMoment: moment.Moment;
  if (dt === "today") {
    dtMoment = moment();
  } else if (dt === "yesterday") {
    dtMoment = moment().subtract(1, "days");
  } else {
    dtMoment = moment(dt);
  }
  const mutationJoplinSync = useJoplinSync({
    mutation: {
      onSuccess: () => setLastSync(new Date()),
    },
  });
  const mutationJoplinInitNote = useJoplinInitNote({ mutation: { retry: 5 } });
  const mutationJoplinUpdateNote = useJoplinUpdateNote({
    mutation: { retry: 5 },
  });
  return (
    <main>
      <Space direction="vertical">
        <DatePicker
          defaultValue={dtMoment}
          onChange={(date: any, dateString: string) => {
            setSearchParams({ dt: dateString });
          }}
        />
        {lastSync ? <p>{`Last Joplin sync: ${lastSync}`}</p> : null}
        {mutationJoplinSync.isLoading && <p>Joplin: currently syncing...</p>}
        <JoplinFindNote
          dt={dt}
          setNoteId={setNoteId}
          lastSync={lastSync}
          setLastSync={setLastSync}
          mutationJoplinSync={mutationJoplinSync}
        />
        {noteId === "does_not_exist" ? (
          <Button
            onClick={() => mutationJoplinInitNote.mutate({ dt: dt })}
            loading={mutationJoplinInitNote.isLoading}
          >
            Init Note
          </Button>
        ) : (
          <Button
            onClick={() => mutationJoplinUpdateNote.mutate({ dt: dt })}
            loading={mutationJoplinUpdateNote.isLoading}
          >
            Update Note: {dt}
          </Button>
        )}
        {mutationJoplinInitNote.isError && (
          <Alert
            message={`Error: ${mutationJoplinInitNote.error.message}`}
            type="error"
          />
        )}
        {mutationJoplinInitNote.isSuccess && (
          <Alert message={`Init note: success`} type="success" closable />
        )}
        {mutationJoplinUpdateNote.isError && (
          <Alert
            message={`Error: ${mutationJoplinUpdateNote.error.message}`}
            type="error"
          />
        )}
        {mutationJoplinUpdateNote.isSuccess && (
          <Alert message={`Update note: success`} type="success" closable />
        )}
      </Space>
    </main>
  );
};

export default TestJoplin;
