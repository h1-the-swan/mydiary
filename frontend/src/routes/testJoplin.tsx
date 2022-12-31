import React, { useCallback, useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Form, Button, Alert, DatePicker, Space, Divider, Collapse } from "antd";
import { useJoplinSync, useJoplinInitNote, useJoplinUpdateNote } from "../api";
import JoplinFindNote from "../components/JoplinFindNote";
import JoplinInitOrUpdateDiaryNote from "../components/JoplinInitOrUpdateDiaryNote";
import moment from "moment";
import GCalRefreshToken from "../components/GCalRefreshToken";

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
  return (
    <main>
      <Collapse defaultActiveKey={"2"}>
        <Collapse.Panel header="Refresh Google Calendar Token" key="1">
          <GCalRefreshToken />
        </Collapse.Panel>
        <Divider />
        <Collapse.Panel header="Initialize or Update Joplin Note" key="2">
          <Space direction="vertical">
            <JoplinInitOrUpdateDiaryNote dt={dt} />
          </Space>
        </Collapse.Panel>
      </Collapse>
    </main>
  );
};

export default TestJoplin;
