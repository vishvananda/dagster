import * as React from "react";
import styled from "styled-components";
import { Colors, Spinner, Intent } from "@blueprintjs/core";
import { IStepState, IStepMaterialization } from "./RunMetadataProvider";
import { ROOT_SERVER_URI } from "../Util";

interface IExecutionPlanBoxProps {
  state: IStepState;
  name: string;
  start: number | undefined;
  elapsed: number | undefined;
  delay: number;
  materializations: IStepMaterialization[];
  onShowStateDetails: (stepName: string) => void;
  onApplyStepFilter: (stepName: string) => void;
}

interface IExecutionPlanBoxState {
  v: number;
}

function twoDigit(v: number) {
  return `${v < 10 ? "0" : ""}${v}`;
}

function fileLocationToHref(location: string) {
  if (location.startsWith("/")) {
    return `file://${location}`;
  }
  return location;
}

export class ExecutionPlanBox extends React.Component<
  IExecutionPlanBoxProps,
  IExecutionPlanBoxState
> {
  state = {
    v: 0
  };

  timer?: NodeJS.Timer;

  shouldComponentUpdate(
    nextProps: IExecutionPlanBoxProps,
    nextState: IExecutionPlanBoxState
  ) {
    return (
      nextProps.state !== this.props.state ||
      nextProps.name !== this.props.name ||
      nextProps.elapsed !== this.props.elapsed ||
      nextState.v !== this.state.v
    );
  }

  componentDidMount() {
    this.ensureTimer();
  }

  componentDidUpdate() {
    this.ensureTimer();
  }

  componentWillUnmount() {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }
  }

  ensureTimer = () => {
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = undefined;
    }

    const { state, start } = this.props;

    // Schedule another update of the component when the elapsed time
    // since the `start` timestamp crosses another 1s boundary.
    if (state === IStepState.RUNNING && start) {
      const nextMs = 1000 - ((Date.now() - start) % 1000);
      this.timer = setTimeout(this.onTick, nextMs);
    }
  };

  onTick = () => {
    // bogus state change to trigger a re-render
    this.setState({ v: this.state.v + 1 });
  };

  onOpenFileLink = async (event: React.MouseEvent<HTMLAnchorElement>) => {
    const url = event.currentTarget.href;

    // If the file's location is a path, tell dagit to open it on the machine.
    if (url.startsWith("file://")) {
      event.preventDefault();

      const path = url.replace("file://", "");
      const result = await fetch(
        `${ROOT_SERVER_URI}/dagit/open?path=${encodeURIComponent(path)}`
      );

      if (result.status !== 200) {
        const error = await result.text();
        alert(`Dagit was unable to open the file.\n\n${error}`);
      }
    } else {
      // If the file's location is a URL, allow the browser to open it normally.
    }
  };

  render() {
    const {
      state,
      start,
      name,
      delay,
      materializations,
      onApplyStepFilter,
      onShowStateDetails
    } = this.props;

    let elapsed = this.props.elapsed;
    if (state === IStepState.RUNNING && start) {
      elapsed = Math.floor((Date.now() - start) / 1000) * 1000;
    }

    return (
      <>
        <ExecutionPlanBoxContainer
          state={state}
          className={state}
          style={{ transitionDelay: `${delay}ms` }}
          onClick={() => onApplyStepFilter(name)}
        >
          <ExecutionFinishedFlash
            style={{ transitionDelay: `${delay}ms` }}
            success={state === IStepState.SUCCEEDED}
          />
          <ExeuctionStateWrap onClick={() => onShowStateDetails(name)}>
            {state === IStepState.RUNNING ? (
              <Spinner intent={Intent.NONE} size={11} />
            ) : (
              <ExecutionStateDot
                state={state}
                style={{ transitionDelay: `${delay}ms` }}
              />
            )}
          </ExeuctionStateWrap>
          <ExecutionPlanBoxName>{name}</ExecutionPlanBoxName>
          {elapsed !== undefined && <ExecutionTime elapsed={elapsed} />}
        </ExecutionPlanBoxContainer>
        {(materializations || []).map(mat => (
          <MaterializationLink
            onClick={this.onOpenFileLink}
            href={fileLocationToHref(mat.fileLocation)}
            key={mat.fileLocation}
            title={mat.fileLocation}
            target="__blank"
          >
            {FileIcon} {mat.fileName}
          </MaterializationLink>
        ))}
      </>
    );
  }
}

const MaterializationLink = styled.a`
  display: block;
  color: ${Colors.GRAY3};
  display: inline-block;
  padding: 6px 3px;
  padding-left: 23px;
  display: inline-flex;
  font-size: 12px;
  &:hover {
    color: ${Colors.WHITE};
  }
`;

const ExeuctionStateWrap = styled.div`
  display: inherit;
  margin-right: 9px;
`;

const ExecutionStateDot = styled.div<{ state: IStepState }>`
  display: inline-block;
  width: 11px;
  height: 11px;
  border-radius: 5.5px;
  transition: background 200ms linear;
  background: ${({ state }) =>
    ({
      [IStepState.WAITING]: Colors.GRAY1,
      [IStepState.RUNNING]: Colors.GRAY3,
      [IStepState.SUCCEEDED]: Colors.GREEN2,
      [IStepState.FAILED]: Colors.RED3
    }[state])};
  &:hover {
    background: ${({ state }) =>
      ({
        [IStepState.WAITING]: Colors.GRAY1,
        [IStepState.RUNNING]: Colors.GRAY3,
        [IStepState.SUCCEEDED]: Colors.GREEN2,
        [IStepState.FAILED]: Colors.RED5
      }[state])};
  }
`;

const ExecutionTime = ({ elapsed }: { elapsed: number }) => {
  let text = "";

  if (elapsed < 1000) {
    // < 1 second, show "X msec"
    text = `${Math.ceil(elapsed)} msec`;
  } else {
    // < 1 hour, show "42:12"
    const sec = Math.floor(elapsed / 1000) % 60;
    const min = Math.floor(elapsed / 1000 / 60) % 60;
    const hours = Math.floor(elapsed / 1000 / 60 / 60);

    if (hours > 0) {
      text = `${hours}:${twoDigit(min)}:${twoDigit(sec)}`;
    } else {
      text = `${min}:${twoDigit(sec)}`;
    }
  }

  // Note: Adding a min-width prevents the size of the execution plan box from
  // shifting /slightly/ as the elapsed time increments.
  return (
    <ExecutionTimeContainer style={{ minWidth: text.length * 6.8 }}>
      {text}
    </ExecutionTimeContainer>
  );
};

const ExecutionTimeContainer = styled.div`
  opacity: 0.7;
  font-size: 0.9em;
  margin-left: 10px;
`;

const ExecutionPlanBoxName = styled.div`
  font-weight: 500;
`;

const ExecutionFinishedFlash = styled.div<{ success: boolean }>`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    111deg,
    transparent 30%,
    rgba(255, 255, 255, 0.7) 65%,
    transparent 68%
  );
  background-size: 150px;
  background-position-x: ${({ success }) =>
    success ? `calc(100% + 150px)` : `-150px`};
  background-repeat: no-repeat;
  pointer-events: none;
  transition: ${({ success }) =>
    success ? "400ms background-position-x linear" : ""};
`;

const ExecutionPlanBoxContainer = styled.div<{ state: IStepState }>`
  background: ${({ state }) =>
    state === IStepState.WAITING ? Colors.GRAY3 : Colors.LIGHT_GRAY2}
  box-shadow: 0 2px 3px rgba(0, 0, 0, 0.3);
  color: ${Colors.DARK_GRAY3};
  padding: 4px;
  padding-right: 10px;
  margin: 6px;
  margin-left: 15px;
  margin-bottom: 0;
  display: inline-flex;
  min-width: 150px;
  align-items: center;
  border-radius: 3px;
  position: relative;
  z-index: 2;
  transition: background 200ms linear;
  border: 2px solid transparent;
  &:hover {
    cursor: default;
    color: ${Colors.BLACK};
    border: 2px solid ${({ state }) =>
      state === IStepState.WAITING ? Colors.LIGHT_GRAY4 : Colors.WHITE};
  }
`;

const FileIcon = (
  <svg width="20px" height="14px" viewBox="-100 0 350 242" version="1.1">
    <g stroke="none" strokeWidth="1" fill="none" fillRule="evenodd">
      <path
        d="M-100,96 L0,96"
        stroke={Colors.GRAY3}
        strokeWidth="15"
        strokeLinecap="square"
      />
      <polygon
        stroke={Colors.GRAY3}
        strokeWidth="15"
        points="5.4296875 236.507812 5.4296875 5.84765625 137.851562 5.84765625 188.003906 56 188.003906 236.507812"
      />
      <path
        d="M187.5,62.5078125 L130.5,62.5078125 M130.5,5.84765625 L130.5,62.5078125"
        stroke={Colors.GRAY3}
        strokeWidth="15"
        strokeLinecap="square"
      />
    </g>
  </svg>
);
