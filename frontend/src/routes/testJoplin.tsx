import React, { useCallback, useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Form, Button, Alert, DatePicker, Space } from "antd";
import { useJoplinSync, useJoplinInitNote } from "../api";
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
  const mutationJoplinInitNote = useJoplinInitNote();
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
        {noteId === "does_not_exist" && (
          <Button
            onClick={() => mutationJoplinInitNote.mutate({ dt: dt })}
            loading={mutationJoplinInitNote.isLoading}
          >
            Init Note
          </Button>
        )}
        {mutationJoplinInitNote.isError && (
          <Alert
            message={`Error: ${mutationJoplinInitNote.error.message}`}
            type="error"
          />
        )}
        {mutationJoplinInitNote.isSuccess && (
          <Alert
            message={`Init note: success`}
            type="success"
          />
        )}
      </Space>
    </main>
  );
};

export default TestJoplin;
